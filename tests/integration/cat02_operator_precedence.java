public class TestPrecedence {
    public static void main(String[] args) {
        int result = 2 + 3 * 4;
        System.out.println(result);
        result = (2 + 3) * 4;
        System.out.println(result);
        result = 10 - 4 - 2;
        System.out.println(result);
    }
}