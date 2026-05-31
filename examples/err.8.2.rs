// 错误示例 8.2 — 数组字面量大小与类型错误
// 预期语义错误：
//   (1) 初始化元素数量与数组声明大小不一致
//   (2) 初始化元素类型与数组元素类型不一致（嵌套数组）

fn err_array_wrong_count(mut a: i32) {
    let mut b: [i32; 2];
    b = [1, 2, 3];
}

fn err_array_wrong_elem_type() {
    let mut a: [[i32; 1]; 1];
    a = [1];
}
#
