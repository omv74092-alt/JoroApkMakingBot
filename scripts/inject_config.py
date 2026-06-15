#!/usr/bin/env python3
"""Injects user config into Android project before build"""
import argparse, os, re

def inject(args):
    # strings.xml — app name + url
    strings_path = "app/src/main/res/values/strings.xml"
    if os.path.exists(strings_path):
        with open(strings_path, "r") as f:
            content = f.read()
        content = re.sub(r'<string name="app_name">.*?</string>',
                         f'<string name="app_name">{args.app_name}</string>', content)
        content = re.sub(r'<string name="app_url">.*?</string>',
                         f'<string name="app_url">{args.url}</string>', content)
        with open(strings_path, "w") as f:
            f.write(content)

    # build.gradle — package name
    gradle_path = "app/build.gradle"
    if os.path.exists(gradle_path):
        with open(gradle_path, "r") as f:
            content = f.read()
        content = re.sub(r'applicationId\s+"[^"]*"',
                         f'applicationId "{args.package}"', content)
        with open(gradle_path, "w") as f:
            f.write(content)

    # features config
    config_path = "app/src/main/assets/config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    import json
    config = {
        "app_name":     args.app_name,
        "package":      args.package,
        "app_url":      args.url,
        "shizuku":      args.shizuku == "true",
        "file_manager": args.file_manager == "true",
        "login_screen": args.login_screen == "true",
        "dark_theme":   args.dark_theme == "true",
        "key_system":   args.key_system == "true",
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print("✅ Config injected successfully!")
    print(json.dumps(config, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--app_name"); p.add_argument("--package")
    p.add_argument("--url", default=""); p.add_argument("--shizuku", default="false")
    p.add_argument("--file_manager", default="false"); p.add_argument("--login_screen", default="false")
    p.add_argument("--dark_theme", default="true"); p.add_argument("--key_system", default="false")
    inject(p.parse_args())
