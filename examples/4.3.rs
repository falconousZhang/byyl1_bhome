// 规则 4.3 — 增加 else if（依赖 1.1，扩展 4.1）
// <else部分> -> else if <表达式> <语句块> <else部分>
// 演示：多分支 if-else if-else（来自 PDF 示例 program_4_30）

fn program_4_30(a:i32) -> i32 {
    if a>0 {
        return a+1;
    } else if a<0 {
        return a-1;
    } else {
        return 0;
    }
}
#
