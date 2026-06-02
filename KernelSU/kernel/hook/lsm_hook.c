#include <linux/capability.h>

#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 10, 0) || defined(CONFIG_IS_HW_HISI) ||                                     \
    defined(CONFIG_KSU_ALLOWLIST_WORKAROUND)
static int ksu_key_permission(key_ref_t key_ref, const struct cred *cred, unsigned perm)
{
    if (init_session_keyring != NULL) {
        return 0;
    }

    if (strcmp(current->comm, "init")) {
        // we are only interested in `init` process
        return 0;
    }
    init_session_keyring = cred->session_keyring;
    pr_info("kernel_compat: got init_session_keyring\n");
    return 0;
}
#endif

#ifdef CONFIG_KSU_SUSFS
extern u32 susfs_zygote_sid;
extern void disable_seccomp(void);
extern struct work_struct susfs_extra_works;

static inline void ksu_handle_extra_susfs_work(void)
{
    if (work_pending(&susfs_extra_works))
        return;

    schedule_work(&susfs_extra_works);
}

static inline bool ksu_is_current_zygote_compat(void)
{
    return susfs_is_sid_equal(current_cred(), susfs_zygote_sid) ||
           strcmp(current->comm, "zygote") == 0 ||
           strcmp(current->comm, "zygote64") == 0;
}

static inline uid_t ksu_pick_setresuid_target(uid_t ruid, uid_t euid, uid_t suid)
{
    if (ruid != (uid_t)-1)
        return ruid;
    if (euid != (uid_t)-1)
        return euid;
    if (suid != (uid_t)-1)
        return suid;

    return current_uid().val;
}

static inline bool ksu_can_install_manager_fd(uid_t target_uid)
{
    const struct cred *cred = current_cred();

    return current_uid().val == target_uid ||
           ns_capable_setid(cred->user_ns, CAP_SETUID);
}

int ksu_handle_setresuid(uid_t ruid, uid_t euid, uid_t suid)
{
    uid_t target_uid = ksu_pick_setresuid_target(ruid, euid, suid);

    if (likely(ksu_is_manager_appid_valid()) && unlikely(is_uid_manager(target_uid))) {
        if (!ksu_can_install_manager_fd(target_uid)) {
            pr_warn("skip manager fd install for uid %d without CAP_SETUID (comm=%s)\n",
                    target_uid, current->comm);
            return 0;
        }
        disable_seccomp();
        pr_info("install fd for manager: %d (setresuid r=%d e=%d s=%d comm=%s)\n",
                target_uid, ruid, euid, suid, current->comm);
        ksu_install_fd();
        return 0;
    }

    // We only interest in process spwaned by zygote
    if (!ksu_is_current_zygote_compat())
        return 0;

    // Check if spawned process is isolated service first, and force to do umount if so
    if (is_isolated_process(target_uid))
        goto do_umount;

    // we should not umount for webview zygote
    if (unlikely(target_uid == WEBVIEW_ZYGOTE_UID))
        return 0;

    // Check if spawned process is normal user app and needs to be umounted
    if (likely(is_appuid(target_uid) && ksu_uid_should_umount(target_uid)))
        goto do_umount;

    // - Disable seccomp restriction for root allowed apps since running with "su" will disable seccomp anyway
    if (ksu_is_allow_uid_for_current(target_uid))
        disable_seccomp();

    return 0;

do_umount:
    {
        // Handle kernel umount
        ksu_handle_umount(current_uid().val, target_uid);

        // Handle extra susfs work
        ksu_handle_extra_susfs_work();
    }

    // Mark current proc as umounted
    susfs_set_current_proc_umounted();

    return 0;
}
#endif

static inline bool ksu_cred_has_manager_uid(const struct cred *cred, uid_t *out)
{
    uid_t uid;

    if (!ksu_is_manager_appid_valid())
        return false;

    uid = cred->uid.val;
    if (is_uid_manager(uid))
        goto manager_found;

    uid = cred->euid.val;
    if (is_uid_manager(uid))
        goto manager_found;

    uid = cred->suid.val;
    if (is_uid_manager(uid))
        goto manager_found;

    uid = cred->fsuid.val;
    if (is_uid_manager(uid))
        goto manager_found;

    return false;

manager_found:
    if (out)
        *out = uid;
    return true;
}

static int ksu_task_fix_setuid(struct cred *new, const struct cred *old, int flags)
{
    uid_t new_uid;
#ifndef CONFIG_KSU_SUSFS
    uid_t old_uid = 0;
#endif

    if (unlikely(!new || !old))
        return 0;

    new_uid = new->uid.val;
#ifndef CONFIG_KSU_SUSFS
    old_uid = old->uid.val;
#endif

    if (unlikely(ksu_cred_has_manager_uid(new, &new_uid))) {
        disable_seccomp();
        pr_info("install fd for manager: %d (task_fix_setuid flags=%d comm=%s)\n",
                new_uid, flags, current->comm);
        ksu_install_fd();
        return 0;
    }

#ifdef CONFIG_KSU_SUSFS
    return 0;
#else
    if (ksu_is_allow_uid_for_current(new_uid)) {
        disable_seccomp();
    }

    // Handle kernel umount
    ksu_handle_umount(old_uid, new_uid);

    return 0;
#endif
}

static struct security_hook_list ksu_hooks[] = {
#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 10, 0) || defined(CONFIG_IS_HW_HISI) ||                                     \
    defined(CONFIG_KSU_ALLOWLIST_WORKAROUND)
    LSM_HOOK_INIT(key_permission, ksu_key_permission),
#endif
    LSM_HOOK_INIT(task_fix_setuid, ksu_task_fix_setuid),
};

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 8, 0)
static const struct lsm_id ksu_lsmid = {
    .name = "ksu",
    .id = LSM_ID_UNDEF,
};
#endif

void __init ksu_lsm_hook_init(void)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 8, 0)
    security_add_hooks(ksu_hooks, ARRAY_SIZE(ksu_hooks), &ksu_lsmid);
#elif LINUX_VERSION_CODE >= KERNEL_VERSION(4, 11, 0)
    security_add_hooks(ksu_hooks, ARRAY_SIZE(ksu_hooks), "ksu");
#else
    // https://elixir.bootlin.com/linux/v4.10.17/source/include/linux/lsm_hooks.h#L1892
    security_add_hooks(ksu_hooks, ARRAY_SIZE(ksu_hooks));
#endif
    pr_info("LSM hooks initialized.\n");
}

void ksu_lsm_hook_exit(void)
{
}
