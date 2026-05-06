// 规则 7.4 — 循环表达式（依赖 3.1, 5.3，扩展 0.3）
// <可取元素>  -> <loop语句>
// <语句>      -> break <表达式> ';'
// 演示：loop 作为表达式，break 携带返回值（来自 PDF 示例 program_7_4）

fn program_7_4() {
    let mut a = loop {
        break 2;
    };
    a;
}
#
