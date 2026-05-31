// 错误示例 6.3 — 借用规则错误
// 预期语义错误：
//   (1) 可变引用与不可变引用不能共存
//   (2) 只能从可变变量创建可变引用

fn err_mut_and_imm_coexist() {
    let mut a: i32 = 1;
    let b = &a;
    let mut c = &mut a;
}

fn err_mut_ref_of_immutable() {
    let a: i32 = 1;
    let mut b = &mut a;
}
#
