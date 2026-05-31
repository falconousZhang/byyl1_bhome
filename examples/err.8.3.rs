// 错误示例 8.3 — 数组访问错误
// 预期语义错误：
//   (1) 索引类型不是 i32（比较表达式结果）
//   (2) 常量索引越界

fn err_index_type() {
    let mut a: [i32; 3] = [1, 2, 3];
    let mut b: i32 = a[1 == 1];
}

fn err_index_out_of_bounds() {
    let mut a: [i32; 3] = [1, 2, 3];
    let mut b: i32 = a[3];
}
#
