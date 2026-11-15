"""
MuMu Player 12 Manager & Automation Helper.
Integrates with native mumu-cli.exe to manage instances, auto-clone,
set FPS limits, adjust resolutions, and display live farm status.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Optional, Any

class MuMuManagerCLI:
    MUMU_CLI = r"C:\Program Files\Netease\MuMuPlayer\nx_main\mumu-cli.exe"

    @classmethod
    def is_available(cls) -> bool:
        return os.path.isfile(cls.MUMU_CLI)

    @classmethod
    def _run_cli(cls, args: List[str]) -> subprocess.CompletedProcess:
        cmd = [cls.MUMU_CLI] + args
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")

    @classmethod
    def get_instances_info(cls) -> Dict[str, Any]:
        """Returns structured dictionary of all created MuMu Player 12 instances."""
        res = cls._run_cli(["info", "-v", "all"])
        if res.returncode == 0 and res.stdout:
            try:
                return json.loads(res.stdout)
            except Exception:
                pass
        return {}

    @classmethod
    def launch_instance(cls, vm_index: int = 0) -> bool:
        """Launches target emulator instance."""
        res = cls._run_cli(["control", "-v", str(vm_index), "-a", "launch"])
        return res.returncode == 0

    @classmethod
    def close_instance(cls, vm_index: int = 0) -> bool:
        """Closes target emulator instance."""
        res = cls._run_cli(["control", "-v", str(vm_index), "-a", "close"])
        return res.returncode == 0

    @classmethod
    def clone_instance(cls, source_vm: int = 0, name: Optional[str] = None) -> bool:
        """Clones an existing instance (copies game & data)."""
        args = ["clone", "-v", str(source_vm)]
        if name:
            args += ["--name", name]
        res = cls._run_cli(args)
        return res.returncode == 0

    @classmethod
    def set_instance_performance(
        cls,
        vm_index: int = 0,
        fps: int = 20,
        width: int = 1280,
        height: int = 720,
        dpi: int = 160,
        cpu: int = 2,
        mem: int = 2
    ) -> bool:
        """Programmatically configures resolution, FPS cap, CPU and RAM."""
        settings = [
            ("--key", "max_frame_rate", "--value", str(fps)),
            ("--key", "dynamic_low_frame_rate_limit", "--value", str(fps)),
            ("--key", "resolution_width", "--value", f"{width}.000000"),
            ("--key", "resolution_height", "--value", f"{height}.000000"),
            ("--key", "resolution_dpi", "--value", f"{dpi}.000000"),
            ("--key", "vm_cpu", "--value", str(cpu)),
            ("--key", "vm_mem", "--value", str(mem)),
        ]
        success = True
        for k_flag, k_val, v_flag, v_val in settings:
            res = cls._run_cli(["setting", "-v", str(vm_index), k_flag, k_val, v_flag, v_val])
            if res.returncode != 0:
                success = False
        return success

    @classmethod
    def arrange_windows_grid(cls) -> bool:
        """Arranges all open emulator windows in a neat grid on your monitor."""
        res = cls._run_cli(["sort"])
        return res.returncode == 0

def print_instances_table():
    info = MuMuManagerCLI.get_instances_info()
    if not info:
        print("[!] Не удалось получить список инстансов MuMu Player 12.")
        return

    print("\n" + "="*75)
    print("           СПИСОК УСТРОЙСТВ MUMU PLAYER 12 (ФЕРМА)")
    print("="*75)
    print(f"{'INDEX':<7} {'NAME':<20} {'STATE':<16} {'ADB PORT':<12} {'PID':<8}")
    print("-" * 75)

    for idx, data in info.items():
        name = data.get("name", f"Instance {idx}")
        state = data.get("player_state", "unknown")
        port = data.get("adb_port", "N/A")
        pid = data.get("pid", "N/A")
        state_str = "РАБОТАЕТ" if state == "start_finished" else state.upper()
        print(f"{idx:<7} {name:<20} {state_str:<16} {str(port):<12} {str(pid):<8}")
    print("="*75 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MuMu Player 12 CLI Assistant")
    parser.add_argument("action", choices=["list", "optimize", "clone", "sort", "launch", "close"], default="list", nargs="?")
    parser.add_argument("--index", type=int, default=0, help="Target instance index")
    parser.add_argument("--fps", type=int, default=20, help="Target FPS limit")
    parser.add_argument("--res", type=str, default="1280x720", help="Resolution (e.g. 1280x720 or 1600x900)")
    parser.add_argument("--name", type=str, default=None, help="Name for cloned instance")

    args = parser.parse_args()

    if args.action == "list":
        print_instances_table()
    elif args.action == "optimize":
        w, h = map(int, args.res.split("x"))
        dpi = 160 if w <= 1280 else 240
        print(f"[*] Применяем оптимизацию к инстансу {args.index}: FPS={args.fps}, Res={w}x{h} (DPI {dpi})...")
        ok = MuMuManagerCLI.set_instance_performance(args.index, fps=args.fps, width=w, height=h, dpi=dpi)
        print("[+] Настройки успешно сохранены!" if ok else "[!] Часть настроек не применилась.")
    elif args.action == "clone":
        print(f"[*] Клонируем инстанс {args.index} (с установленной Матрёшкой RP)...")
        ok = MuMuManagerCLI.clone_instance(args.index, args.name)
        print("[+] Клонирование завершено!" if ok else "[!] Ошибка клонирования.")
    elif args.action == "sort":
        print("[*] Выравниваем окна на экране сеткой...")
        MuMuManagerCLI.arrange_windows_grid()
        print("[+] Окна упорядочены!")
    elif args.action == "launch":
        print(f"[*] Запуск инстанса {args.index}...")
        MuMuManagerCLI.launch_instance(args.index)
    elif args.action == "close":
        print(f"[*] Закрытие инстанса {args.index}...")
        MuMuManagerCLI.close_instance(args.index)
