#ifndef KSU_SUSFS_DEF_H
#define KSU_SUSFS_DEF_H

#include <linux/bits.h>
#include <linux/cred.h>
#include <linux/sched.h>
#include <linux/string.h>
#include <linux/thread_info.h>

/* shared with userspace ksu_susfs tool */
#define SUSFS_MAGIC 0xFAFAFAFA
#define CMD_SUSFS_ADD_SUS_PATH 0x55550
#define CMD_SUSFS_SET_ANDROID_DATA_ROOT_PATH 0x55551 /* deprecated */
#define CMD_SUSFS_SET_SDCARD_ROOT_PATH 0x55552 /* deprecated */
#define CMD_SUSFS_ADD_SUS_PATH_LOOP 0x55553
#define CMD_SUSFS_ADD_SUS_MOUNT 0x55560 /* deprecated */
#define CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS 0x55561
#define CMD_SUSFS_UMOUNT_FOR_ZYGOTE_ISO_SERVICE 0x55562 /* deprecated */
#define CMD_SUSFS_ADD_SUS_KSTAT 0x55570
#define CMD_SUSFS_UPDATE_SUS_KSTAT 0x55571
#define CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY 0x55572
#define CMD_SUSFS_ADD_TRY_UMOUNT 0x55580 /* deprecated */
#define CMD_SUSFS_SET_UNAME 0x55590
#define CMD_SUSFS_ENABLE_LOG 0x555a0
#define CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG 0x555b0
#define CMD_SUSFS_ADD_OPEN_REDIRECT 0x555c0
#define CMD_SUSFS_SHOW_VERSION 0x555e1
#define CMD_SUSFS_SHOW_ENABLED_FEATURES 0x555e2
#define CMD_SUSFS_SHOW_VARIANT 0x555e3
#define CMD_SUSFS_SHOW_SUS_SU_WORKING_MODE 0x555e4 /* deprecated */
#define CMD_SUSFS_IS_SUS_SU_READY 0x555f0 /* deprecated */
#define CMD_SUSFS_SUS_SU 0x60000 /* deprecated */
#define CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING 0x60010
#define CMD_SUSFS_ADD_SUS_MAP 0x60020

#define SUSFS_MAX_LEN_PATHNAME 256
#define SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE 8192
#define SUSFS_ENABLED_FEATURES_SIZE 8192
#define SUSFS_MAX_VERSION_BUFSIZE 16
#define SUSFS_MAX_VARIANT_BUFSIZE 16

#define TRY_UMOUNT_DEFAULT 0
#define TRY_UMOUNT_DETACH 1

#define VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT 0x80000000
#define DEFAULT_KSU_MNT_ID 500000
#define DEFAULT_KSU_MNT_GROUP_ID 5000

#ifndef FUSE_SUPER_MAGIC
#define FUSE_SUPER_MAGIC 0x65735546
#endif

#define TIF_PROC_UMOUNTED 33

#define AS_FLAGS_SUS_PATH 33
#define AS_FLAGS_SUS_MOUNT 34
#define AS_FLAGS_SUS_KSTAT 35
#define AS_FLAGS_OPEN_REDIRECT 36
#define AS_FLAGS_SUS_MAP 39

#define ND_STATE_LOOKUP_LAST 32
#define ND_STATE_OPEN_LAST 64
#define ND_FLAGS_LOOKUP_LAST 0x2000000

#define MAGIC_MOUNT_WORKDIR "/debug_ramdisk/workdir"

extern bool susfs_is_current_ksu_domain(void);
extern bool susfs_is_current_zygote_domain(void);
extern bool susfs_is_current_init_domain(void);

static inline bool susfs_is_host_manager_process(void)
{
	if (!current)
		return true;

	return !strncmp(current->comm, "systemd", sizeof("systemd") - 1) ||
	       !strcmp(current->comm, "init") ||
	       !strcmp(current->comm, "udevd") ||
	       !strncmp(current->comm, "dbus-", sizeof("dbus-") - 1) ||
	       !strncmp(current->comm, "sddm", sizeof("sddm") - 1) ||
	       !strcmp(current->comm, "NetworkManager") ||
	       !strcmp(current->comm, "pacman") ||
	       !strcmp(current->comm, "mkinitcpio");
}

static inline bool susfs_should_apply_to_current(void)
{
	if (!current)
		return false;

	if (current->pid == 1)
		return false;

	if (current->flags & PF_KTHREAD)
		return false;

	if (susfs_is_host_manager_process())
		return false;

	if (susfs_is_current_ksu_domain())
		return true;

	if (test_thread_flag(TIF_PROC_UMOUNTED))
		return true;

	return false;
}

static inline bool susfs_can_mark_current_proc_umounted(void)
{
	if (!current)
		return false;

	if (current->pid == 1)
		return false;

	if (current->flags & PF_KTHREAD)
		return false;

	if (susfs_is_host_manager_process())
		return false;

	if (susfs_is_current_ksu_domain() ||
	    susfs_is_current_zygote_domain() ||
	    susfs_is_current_init_domain())
		return true;

	return false;
}

static inline bool susfs_may_handle_android_exec(const char *pathname)
{
	if (!pathname)
		return false;

	if (susfs_should_apply_to_current())
		return true;

	if (susfs_is_host_manager_process())
		return false;

	return !strncmp(pathname, "/system/", sizeof("/system/") - 1) ||
	       !strncmp(pathname, "/vendor/", sizeof("/vendor/") - 1) ||
	       !strncmp(pathname, "/odm/", sizeof("/odm/") - 1) ||
	       !strncmp(pathname, "/apex/", sizeof("/apex/") - 1) ||
	       !strncmp(pathname, "/data/adb/", sizeof("/data/adb/") - 1) ||
	       !strcmp(pathname, "/init");
}

static inline bool susfs_starts_with(const char *str, const char *prefix)
{
	while (*prefix) {
		if (*str++ != *prefix++)
			return false;
	}
	return true;
}

static inline bool susfs_ends_with(const char *str, const char *suffix)
{
	size_t str_len, suffix_len;

	if (!str || !suffix)
		return false;

	str_len = strlen(str);
	suffix_len = strlen(suffix);

	if (suffix_len > str_len)
		return false;

	return !strcmp(str + str_len - suffix_len, suffix);
}

static inline bool susfs_is_current_proc_umounted(void)
{
	return likely(test_thread_flag(TIF_PROC_UMOUNTED)) &&
	       susfs_should_apply_to_current();
}

static inline void susfs_set_current_proc_umounted(void)
{
	if (susfs_can_mark_current_proc_umounted())
		set_thread_flag(TIF_PROC_UMOUNTED);
}

static inline bool susfs_is_current_proc_umounted_app(void)
{
	return likely(test_thread_flag(TIF_PROC_UMOUNTED)) &&
	       susfs_should_apply_to_current() &&
	       current_uid().val >= 10000;
}

#define SUSFS_IS_INODE_SUS_MAP(inode) \
	((inode) && (inode)->i_mapping && \
	 unlikely(test_bit(AS_FLAGS_SUS_MAP, &(inode)->i_mapping->flags)) && \
	 susfs_is_current_proc_umounted_app())

#define SUSFS_IS_INODE_OPEN_REDIRECT_WITHOUT_UID_CHECK(inode) \
	((inode) && (inode)->i_mapping && \
	 susfs_should_apply_to_current() && \
	 unlikely(test_bit(AS_FLAGS_OPEN_REDIRECT, &(inode)->i_mapping->flags)))

#define SUSFS_IS_INODE_OPEN_REDIRECT(inode) \
	((inode) && (inode)->i_mapping && \
	 unlikely(test_bit(AS_FLAGS_OPEN_REDIRECT, &(inode)->i_mapping->flags)) && \
	 susfs_is_current_proc_umounted_app())

#endif
