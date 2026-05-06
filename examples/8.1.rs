// 规则 8.1 — 数组类型（依赖 0.2，扩展 0.2）
// <类型> -> '[' <类型> ';' <NUM> ']'
// 演示：一维/嵌套数组类型注解（来自 PDF 示例 program_8_10）

fn program_8_10() {
    let mut a:[i32;3];
}

fn program_8_11() {
    let mut a:[i32;5];
    let mut b:[[i32;3];2];
}
#
