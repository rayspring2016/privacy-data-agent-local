#!/usr/bin/env bash
# 把 pda_inbox/ 里的原始文件跑一遍本地脱敏，结果放进 pda_outbox/，
# 原始文件挪到 pda_inbox/已处理/ 存档（不删，避免误丢数据）。
# 用法：把文件拖进 pda_inbox/，然后跑 ./process_inbox.sh（或在 Claude Code 里说"处理一下"）。
set -euo pipefail
cd "$(dirname "$0")"

INBOX="pda_inbox"
OUTBOX="pda_outbox"
PROCESSED="$INBOX/已处理"

mkdir -p "$OUTBOX" "$PROCESSED"

shopt -s nullglob
files=("$INBOX"/*.xlsx "$INBOX"/*.xls "$INBOX"/*.csv "$INBOX"/*.docx "$INBOX"/*.pdf)

if [ ${#files[@]} -eq 0 ]; then
    echo "pda_inbox/ 里没有待处理文件。"
    exit 0
fi

for f in "${files[@]}"; do
    name="$(basename "$f")"
    stem="${name%.*}"
    ts="$(date +%Y%m%d_%H%M%S)"
    out_dir="$OUTBOX/${stem}_${ts}"
    echo "处理: $name"
    uv run privacy-data-agent anonymize "$f" --output-dir "$out_dir"
    mv "$f" "$PROCESSED/$name"
    echo "  -> 脱敏结果: $out_dir/"
    echo "  -> 原始文件已存档: $PROCESSED/$name"
done

echo ""
echo "全部处理完成。原始文件已从 pda_inbox 移出，只有脱敏后的结果留在 pda_outbox/。"
