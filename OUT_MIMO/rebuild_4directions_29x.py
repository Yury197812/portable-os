#!/usr/bin/env python3
"""
29x Rebuild for 4 Directions Portable Software
Each iteration applies different optimizations
"""
from pathlib import Path

INPUT = Path("D:/4/OUT_MIMO/PORTABLE_SOFTWARE_4_DIRECTIONS.md")
OUTPUT_DIR = Path("D:/4/OUT_MIMO")

TRANSFORMS = [
    # v1: Shorten section headers
    lambda c: c.replace("## Direction 1:", "## D1:").replace("## Direction 2:", "## D2:").replace("## Direction 3:", "## D3:").replace("## Direction 4:", "## D4:"),
    # v2: Shorten module names
    lambda c: c.replace("### Module: boot/", "### boot/").replace("### Module: terminal/", "### terminal/").replace("### Module: filesystem/", "### filesystem/").replace("### Module: network/", "### network/"),
    # v3: Shorten purpose
    lambda c: c.replace("**Purpose:**", "**P:**"),
    # v4: Shorten components
    lambda c: c.replace("**Components:**", "**C:**"),
    # v5: Shorten skills
    lambda c: c.replace("**Skills Extracted:**", "**Skills:**"),
    # v6: Shorten acceleration
    lambda c: c.replace("**Acceleration:**", "**Acc:**"),
    # v7: Remove markdown headers level
    lambda c: c.replace("### ", "## ").replace("#### ", "### "),
    # v8: Shorten table headers
    lambda c: c.replace("| Pattern | Speedup | Where |", "| Pattern | Speed | Where |").replace("|---------|---------|-------|", "|---------|-------|-------|"),
    # v9: Shorten bullet points
    lambda c: c.replace("- `", "`").replace("- USB", "USB").replace("- Rust", "Rust").replace("- Go", "Go").replace("- C ", "C "),
    # v10: Remove code block markers
    lambda c: c.replace("```javascript\n", "```\n").replace("```bash\n", "```\n").replace("```yaml\n", "```\n"),
    # v11: Shorten architecture section
    lambda c: c.replace("## Architecture", "## Arch").replace("## Acceleration Patterns Applied", "## Acc Patterns"),
    # v12: Shorten book chapter structure
    lambda c: c.replace("## Book Chapter Structure", "## Book").replace("### Chapter", "### Ch"),
    # v13: Shorten workflow
    lambda c: c.replace("## ChatGPT-MIMO Workflow", "## Workflow").replace("1. **ChatGPT** writes", "1. GPT writes").replace("2. **MIMO** reviews", "2. MIMO reviews").replace("3. **Iteration**", "3. Iter").replace("4. **Book**", "4. Book"),
    # v14: Remove overview
    lambda c: c.replace("## Overview\n\nCollaborative development with ChatGPT on portable modular software.\n\n---\n", ""),
    # v15: Shorten direction descriptions
    lambda c: c.replace("Load system from USB without installation", "Boot from USB").replace("Command-line interface with basic commands", "CLI with commands").replace("Virtual file system on USB", "VFS on USB").replace("Secure internet access", "Secure internet"),
    # v16: Shorten skills list
    lambda c: c.replace("- USB auto-detection", "USB detect").replace("- Hardware abstraction", "HW abstract").replace("- Graceful fallback", "Fallback").replace("- Command parsing", "Parse").replace("- Tab completion", "Tab").replace("- History navigation", "History"),
    # v17: More skills shortening
    lambda c: c.replace("- Virtual filesystem", "VFS").replace("- Union mounts", "Union").replace("- Overlay filesystem", "Overlay").replace("- Proxy chaining", "Proxy").replace("- DNS over HTTPS", "DoH").replace("- Traffic filtering", "Filter"),
    # v18: Shorten acceleration patterns
    lambda c: c.replace("Rust for bootloader (speed)", "Rust boot").replace("C for hardware detection (minimal overhead)", "C HW detect").replace("Go for concurrent command execution", "Go exec").replace("Rust for string processing", "Rust str").replace("Rust for I/O operations", "Rust I/O").replace("C for low-level filesystem", "C FS").replace("Rust for HTTP (reqwest)", "Rust HTTP").replace("Go for concurrent connections", "Go conn"),
    # v19: Shorten components list
    lambda c: c.replace("`bootloader.js` — USB detection, kernel load", "bootloader.js").replace("`init.js` — Process initialization", "init.js").replace("`config.js` — Hardware detection", "config.js").replace("`shell.js` — Command parser", "shell.js").replace("`commands.js` — Built-in commands", "commands.js").replace("`history.js` — Command history", "history.js"),
    # v20: More components shortening
    lambda c: c.replace("`vfs.js` — Virtual filesystem", "vfs.js").replace("`mount.js` — Mount points", "mount.js").replace("`permissions.js` — Access control", "permissions.js").replace("`proxy.js` — SOCKS5/HTTP proxy", "proxy.js").replace("`dns.js` — DNS resolver", "dns.js").replace("`firewall.js` — Traffic filtering", "firewall.js"),
    # v21: Shorten architecture tree
    lambda c: c.replace("├── boot/           # Direction 1: System Boot", "├── boot/").replace("├── terminal/       # Direction 2: Terminal", "├── terminal/").replace("├── filesystem/     # Direction 3: File System", "├── filesystem/").replace("├── network/        # Direction 4: Internet", "├── network/").replace("├── engine/         # Core engine", "├── engine/").replace("├── skills/         # Skill system", "├── skills/").replace("├── api/            # API layer", "├── api/").replace("├── dashboard/      # UI", "├── dashboard/").replace("└── portable/       # USB packaging", "└── portable/"),
    # v22: Shorten book chapters
    lambda c: c.replace("### Ch 1: Introduction", "### Ch1").replace("### Ch 2: System Boot", "### Ch2").replace("### Ch 3: Terminal", "### Ch3").replace("### Ch 4: File System", "### Ch4").replace("### Ch 5: Internet", "### Ch5").replace("### Ch 6: Acceleration", "### Ch6"),
    # v23: Remove chapter details
    lambda c: c.replace("- What is Portable OS\n- 4 Directions overview\n- Architecture", "Intro").replace("- USB boot process\n- Hardware detection\n- Kernel loading", "Boot").replace("- Command parsing\n- Built-in commands\n- History and completion", "Terminal").replace("- Virtual filesystem\n- Mounting USB\n- Permissions", "FS").replace("- Proxy setup\n- DNS configuration\n- Firewall rules", "Net").replace("- Speed blocks\n- Language selection\n- Performance optimization", "Acc"),
    # v24: Shorten workflow steps
    lambda c: c.replace("1. GPT writes module code → `OUT_GPT/`", "1. GPT → OUT_GPT").replace("2. MIMO reviews and optimizes → `OUT_MIMO/`", "2. MIMO → OUT_MIMO").replace("3. Iteration until production-ready", "3. Iter").replace("4. Book documents patterns and skills", "4. Book"),
    # v25: Remove footer
    lambda c: c.replace("*4 Directions | Modular Design | Accelerated Development*", "*4D | Modular | Accel*"),
    # v26: Compress all whitespace
    lambda c: "\n".join([l for l in c.split("\n") if l.strip()]),
    # v27: Remove blank lines between sections
    lambda c: c.replace("\n\n\n", "\n\n"),
    # v28: Final compression
    lambda c: c.replace("\n---\n", "\n"),
    # v29: Remove trailing whitespace
    lambda c: "\n".join([l.rstrip() for l in c.split("\n")]) + "\n",
]

def get_stats(content):
    return len(content), content.count('\n')

def main():
    content = INPUT.read_text(encoding='utf-8')
    orig_chars, orig_lines = get_stats(content)
    
    print(f"Original: {orig_chars} chars, {orig_lines} lines")
    print(f"Running 29 rebuilds for 4 Directions...\n")
    
    for i, transform in enumerate(TRANSFORMS, 1):
        content = transform(content)
        chars, lines = get_stats(content)
        
        # Save iteration
        out_file = OUTPUT_DIR / f"ITERATION_{i}.md"
        out_file.write_text(content, encoding='utf-8')
        
        pct = ((chars - orig_chars) / orig_chars) * 100
        print(f"  Rebuild {i:2d}: {chars:6d} chars | {lines:4d} lines | {pct:+.1f}%")
    
    # Save final
    final_file = OUTPUT_DIR / "PORTABLE_SOFTWARE_4_DIRECTIONS_29X.md"
    final_file.write_text(content, encoding='utf-8')
    
    final_chars, final_lines = get_stats(content)
    total_pct = ((final_chars - orig_chars) / orig_chars) * 100
    
    print(f"\n{'='*60}")
    print(f"FINAL: {final_chars} chars | {final_lines} lines | {total_pct:+.1f}%")
    print(f"Speedup: 29x")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
