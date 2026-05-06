// 规则 7.1 — 函数表达式块作为表达式（依赖 7.0，扩展 0.3）
// <可取元素> -> <函数表达式语句块>
// 演示：{ ... expr } 块直接用作右值（来自 PDF 示例 program_7_1）

fn program_7_1(mut x:i32, mut y:i32) {
    let mut z = {
        let mut t:i32 = x*x+x;
        t = t + x*y;
        t
    };
    z;
}
#
