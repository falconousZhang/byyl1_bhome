// 规则 5.1 — while 循环（依赖 1.1, 3.1，扩展 5.0）
// <循环语句>  -> <while语句>
// <while语句> -> while <表达式> <语句块>
// 演示：while 递减计数（来自 PDF 示例 program_5_10）

fn program_5_10(mut n:i32) {
    while n>0 {
        n = n-1;
    }
}
#
