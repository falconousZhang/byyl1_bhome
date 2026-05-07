// 进阶示例 2 — 数组操作：最大值、求和、线性查找
// 验证：arr_max([3,1,4,1,5,9])=9, arr_sum([1,2,3,4,5,6])=21, arr_search([10,20,30,40,50,60],30)=2

fn arr_max(a: [i32; 6]) -> i32 {
    let mut mx: i32 = a[0];
    let mut i: i32 = 1;
    while i < 6 {
        if a[i] > mx {
            mx = a[i];
        }
        i = i + 1;
    }
    mx
}

fn arr_sum(a: [i32; 6]) -> i32 {
    let mut s: i32 = 0;
    for x in a {
        s = s + x;
    }
    s
}

fn arr_search(a: [i32; 6], target: i32) -> i32 {
    let mut i: i32 = 0;
    while i < 6 {
        if a[i] == target {
            return i;
        }
        i = i + 1;
    }
    return -1;
}
#
