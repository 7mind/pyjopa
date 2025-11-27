public class TestBitwiseOps {
    public static void main(String[] args) {
        int a = 12;  // 1100
        int b = 10;  // 1010
        System.out.println(a & b);  // 1000 = 8
        System.out.println(a | b);  // 1110 = 14
        System.out.println(a ^ b);  // 0110 = 6
        System.out.println(~a);     // -13
        System.out.println(a << 1); // 24
        System.out.println(a >> 1); // 6
    }
}