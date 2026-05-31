// 错误示例 2.1 — 变量声明无法推断类型
// 预期语义错误：
//   (1) let mut b; 函数结束前始终未赋值，无法推断类型
//   (2) let mut c; 块结束前始终未赋值，无法推断类型
// 对比：
//   let mut a; a=1;  → 合法，类型推断为 i32

fn err_no_init() {
    let mut a: i32 = 0;
    let mut b;
}

fn err_no_init_in_block(mut x: i32) {
    if x > 0 {
        let mut c;
    }
}

fn ok_infer_from_assign() {
    let mut a;
    a = 1;
}
#
