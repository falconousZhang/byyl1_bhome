// 进阶示例 5 — 函数互调与递归：阶乘、递归幂次、斐波那契
// 验证：factorial(5)=120, rec_power(2,8)=256, fib_rec(10)=55

fn factorial(n: i32) -> i32 {
    if n <= 1 {
        return 1;
    }
    return n * factorial(n - 1);
}

fn rec_power(mut base: i32, mut exp: i32) -> i32 {
    if exp == 0 {
        return 1;
    }
    let mut half: i32 = rec_power(base, exp / 2);
    let mut rem: i32 = exp - exp / 2 * 2;
    if rem == 0 {
        return half * half;
    }
    return half * half * base;
}

fn fib_rec(n: i32) -> i32 {
    if n <= 1 {
        return n;
    }
    return fib_rec(n - 1) + fib_rec(n - 2);
}
#
