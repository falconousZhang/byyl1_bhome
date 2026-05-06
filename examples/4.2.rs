// 规则 4.2 — 增加 else（依赖 1.1，扩展 4.1）
// <else部分> -> else <语句块>
// 演示：标准 if-else（来自 PDF 示例 program_4_20）

fn program_4_20(a:i32) -> i32 {
    if a>0 {
        return 1;
    } else {
        return 0;
    }
}
#
