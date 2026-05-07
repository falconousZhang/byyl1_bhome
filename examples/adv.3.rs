// 进阶示例 3 — 排序与统计：冒泡排序、最值元组、点积
// 验证：bubble_sort([5,3,1,4,2])=[1,2,3,4,5], minmax([3,1,4,1,5])=(1,5), dot([1,2,3,4],[4,3,2,1])=20

fn bubble_sort(mut a: [i32; 5]) -> [i32; 5] {
    let mut i: i32 = 0;
    while i < 5 {
        let mut j: i32 = 0;
        while j < 4 - i {
            if a[j] > a[j + 1] {
                let mut t: i32 = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
            j = j + 1;
        }
        i = i + 1;
    }
    a
}

fn minmax(a: [i32; 5]) -> (i32, i32) {
    let mut mn: i32 = a[0];
    let mut mx: i32 = a[0];
    let mut i: i32 = 1;
    while i < 5 {
        if a[i] < mn {
            mn = a[i];
        }
        if a[i] > mx {
            mx = a[i];
        }
        i = i + 1;
    }
    (mn, mx)
}

fn dot_product(a: [i32; 4], b: [i32; 4]) -> i32 {
    let mut s: i32 = 0;
    let mut i: i32 = 0;
    while i < 4 {
        s = s + a[i] * b[i];
        i = i + 1;
    }
    s
}
#
