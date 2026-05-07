// 进阶示例 1 — 数学算法：斐波那契、快速幂、最大公约数
// 每个函数可在执行面板单独验证：fib(10)=55, power(2,10)=1024, gcd(48,18)=6

fn fibonacci(n: i32) -> i32 {
    if n <= 1 {
        return n;
    }
    let mut a: i32 = 0;
    let mut b: i32 = 1;
    let mut i: i32 = 2;
    let mut r: i32 = 1;
    while i <= n {
        r = a + b;
        a = b;
        b = r;
        i = i + 1;
    }
    r
}

fn power(mut base: i32, mut exp: i32) -> i32 {
    let mut result: i32 = 1;
    while exp > 0 {
        let mut rem: i32 = exp - exp / 2 * 2;
        if rem == 1 {
            result = result * base;
        }
        base = base * base;
        exp = exp / 2;
    }
    result
}

fn gcd(mut a: i32, mut b: i32) -> i32 {
    while b != 0 {
        let mut t: i32 = b;
        let mut q: i32 = a / b;
        b = a - q * b;
        a = t;
    }
    a
}
#
