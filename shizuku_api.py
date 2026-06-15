# ============================================================
# shizuku_api.py - Shizuku & ADB Integration
# Root-level operations bina root ke (Shizuku via ADB)
# ============================================================

import subprocess
import logging
import os
import shlex
from config import ADB_PATH, USE_ADB_FALLBACK, SHIZUKU_SOCKET

logger = logging.getLogger(__name__)


class ShizukuRunner:
    """
    Shizuku API wrapper.
    Primary:  Shizuku privileged shell via `adb shell`
    Fallback: Direct `adb shell` commands
    """

    def __init__(self):
        self.adb = ADB_PATH
        self._shizuku_available = None   # cached after first check

    # ── Low-level executor ────────────────────────────────────
    def _exec(self, cmd: str, timeout: int = 30) -> tuple[bool, str]:
        """
        Shell command execute karo.
        Returns (success: bool, output: str)
        """
        try:
            result = subprocess.run(
                cmd, shell=True,
                capture_output=True, text=True,
                timeout=timeout
            )
            output = (result.stdout + result.stderr).strip()
            success = result.returncode == 0
            logger.debug(f"CMD: {cmd!r} | RC={result.returncode}")
            return success, output
        except subprocess.TimeoutExpired:
            return False, "⏱️ Command timed out"
        except Exception as e:
            return False, f"❌ Execution error: {e}"

    def _adb(self, shell_cmd: str, timeout: int = 30) -> tuple[bool, str]:
        """ADB shell ke through command chalao"""
        safe = shell_cmd.replace("'", "'\\''")
        return self._exec(f"{self.adb} shell '{safe}'", timeout)

    # ── Shizuku availability check ────────────────────────────
    def is_shizuku_running(self) -> bool:
        """Check karo ki Shizuku chal raha hai ya nahi"""
        # Method 1: Shizuku socket file check via adb
        ok, out = self._adb(f"ls {SHIZUKU_SOCKET} 2>/dev/null && echo FOUND || echo NOT_FOUND")
        if ok and "FOUND" in out:
            self._shizuku_available = True
            return True

        # Method 2: Shizuku server process check
        ok2, out2 = self._adb("ps -A | grep shizuku 2>/dev/null")
        if ok2 and "shizuku" in out2.lower():
            self._shizuku_available = True
            return True

        # Method 3: pm path check (Shizuku app installed?)
        ok3, out3 = self._adb("pm path moe.shizuku.privileged.api 2>/dev/null")
        if ok3 and "package:" in out3:
            self._shizuku_available = True
            return True

        self._shizuku_available = False
        return False

    def _shizuku_run(self, command: str, timeout: int = 30) -> tuple[bool, str]:
        """
        Shizuku ke zariye command chalao.
        Agar Shizuku na ho to ADB fallback use karo.
        """
        if self.is_shizuku_running():
            # Shizuku rish (privileged shell) use karo
            rish = f"{self.adb} shell sh /sdcard/shizuku/rish -c {shlex.quote(command)}"
            ok, out = self._exec(rish, timeout)
            if ok or not USE_ADB_FALLBACK:
                return ok, out

        # ADB Fallback
        if USE_ADB_FALLBACK:
            return self._adb(command, timeout)

        return False, "❌ Shizuku available nahi hai aur ADB fallback disabled hai"

    # ═══════════════════════════════════════════════════════════
    # PUBLIC METHODS
    # ═══════════════════════════════════════════════════════════

    def run(self, command: str) -> tuple[bool, str]:
        """Koi bhi shell command Shizuku privileges ke saath chalao"""
        logger.info(f"ShizukuRunner.run(): {command!r}")
        return self._shizuku_run(command)

    def install(self, apk_path: str) -> tuple[bool, str]:
        """
        Silent APK install via Shizuku/ADB.
        apk_path: device par APK ka full path ya local path
        """
        # Local path? pehle push karo
        if os.path.isfile(apk_path):
            push_ok, push_out = self._exec(f"{self.adb} push {shlex.quote(apk_path)} /data/local/tmp/_install_.apk")
            if not push_ok:
                return False, f"APK push failed:\n{push_out}"
            device_apk = "/data/local/tmp/_install_.apk"
        else:
            device_apk = apk_path

        # Shizuku se install karo (pm install -r -t)
        ok, out = self._shizuku_run(f"pm install -r -t {shlex.quote(device_apk)}")
        # Cleanup
        self._adb(f"rm -f {shlex.quote(device_apk)}")
        return ok, out

    def grant_permission(self, package: str, permission: str) -> tuple[bool, str]:
        """App ko runtime permission grant karo"""
        cmd = f"pm grant {shlex.quote(package)} {shlex.quote(permission)}"
        return self._shizuku_run(cmd)

    def revoke_permission(self, package: str, permission: str) -> tuple[bool, str]:
        """Runtime permission revoke karo"""
        cmd = f"pm revoke {shlex.quote(package)} {shlex.quote(permission)}"
        return self._shizuku_run(cmd)

    def take_screenshot(self, output_path: str = "/sdcard/screenshot_bot.png") -> tuple[bool, str]:
        """Screenshot lo aur path return karo"""
        ok, out = self._shizuku_run(f"screencap -p {shlex.quote(output_path)}")
        if ok:
            # Pull to local temp
            local = "/tmp/bot_screenshot.png"
            pull_ok, pull_out = self._exec(f"{self.adb} pull {shlex.quote(output_path)} {local}")
            if pull_ok:
                self._adb(f"rm -f {shlex.quote(output_path)}")
                return True, local
            return False, f"Screenshot liya par pull failed:\n{pull_out}"
        return False, out

    def get_device_property(self, prop_name: str) -> tuple[bool, str]:
        """Android system property lo (e.g. ro.build.version.release)"""
        return self._shizuku_run(f"getprop {shlex.quote(prop_name)}")

    def get_device_info(self) -> dict:
        """Device ki puri info ek saath lo"""
        props = {
            "model":        "ro.product.model",
            "brand":        "ro.product.brand",
            "android":      "ro.build.version.release",
            "sdk":          "ro.build.version.sdk",
            "build":        "ro.build.display.id",
            "cpu_abi":      "ro.product.cpu.abi",
            "manufacturer": "ro.product.manufacturer",
            "device":       "ro.product.device",
        }
        info = {}
        for key, prop in props.items():
            ok, val = self.get_device_property(prop)
            info[key] = val.strip() if ok else "Unknown"

        # Battery info
        ok_b, bat = self._shizuku_run("dumpsys battery | grep -E 'level|status|temperature'")
        info["battery"] = bat if ok_b else "Unknown"

        # Uptime
        ok_u, up = self._shizuku_run("uptime -p 2>/dev/null || uptime")
        info["uptime"] = up if ok_u else "Unknown"

        return info

    def list_packages(self, filter_flag: str = "") -> tuple[bool, str]:
        """
        Installed packages list karo.
        filter_flag: '' = all, '-3' = third-party, '-s' = system
        """
        return self._shizuku_run(f"pm list packages {filter_flag} | sort")

    def uninstall(self, package: str, keep_data: bool = False) -> tuple[bool, str]:
        """App uninstall karo"""
        flag = "-k" if keep_data else ""
        return self._shizuku_run(f"pm uninstall {flag} {shlex.quote(package)}")

    def force_stop(self, package: str) -> tuple[bool, str]:
        """App force stop karo"""
        return self._shizuku_run(f"am force-stop {shlex.quote(package)}")

    def clear_data(self, package: str) -> tuple[bool, str]:
        """App data aur cache clear karo"""
        return self._shizuku_run(f"pm clear {shlex.quote(package)}")

    def run_script(self, script_path: str) -> tuple[bool, str]:
        """
        Shell script device par push karke chalao.
        script_path: local bot machine par script ka path
        """
        if not os.path.isfile(script_path):
            return False, f"Script file nahi mili: {script_path}"

        device_path = "/data/local/tmp/_bot_script_.sh"
        push_ok, push_out = self._exec(f"{self.adb} push {shlex.quote(script_path)} {device_path}")
        if not push_ok:
            return False, f"Script push failed:\n{push_out}"

        # Execute aur cleanup
        ok, out = self._shizuku_run(f"sh {device_path}")
        self._adb(f"rm -f {device_path}")
        return ok, out

    def adb_status(self) -> tuple[bool, str]:
        """ADB connection check karo"""
        return self._exec(f"{self.adb} devices")

    def list_dir(self, path: str) -> tuple[bool, str]:
        """Device par directory list karo"""
        return self._shizuku_run(f"ls -la {shlex.quote(path)}")

    def push_file(self, local_path: str, device_path: str) -> tuple[bool, str]:
        """Bot se device par file push karo"""
        return self._exec(f"{self.adb} push {shlex.quote(local_path)} {shlex.quote(device_path)}")

    def pull_file(self, device_path: str, local_path: str) -> tuple[bool, str]:
        """Device se bot par file pull karo"""
        return self._exec(f"{self.adb} pull {shlex.quote(device_path)} {shlex.quote(local_path)}")

    def delete_file(self, device_path: str) -> tuple[bool, str]:
        """Device par file delete karo"""
        return self._shizuku_run(f"rm -f {shlex.quote(device_path)}")

    def exec_at_path(self, user_path: str, command: str) -> tuple[bool, str]:
        """User ke set path par command chalao"""
        full_cmd = f"cd {shlex.quote(user_path)} && {command}"
        return self._shizuku_run(full_cmd)
