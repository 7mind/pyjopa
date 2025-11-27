public class TestTernary {
    public static void main(String[] args) {
        int a = 10;
        int b = 20;
        int max = (a > b) ? a : b;
        System.out.println(max);
        String result = (a == 10) ? "yes" : "no";
        System.out.println(result);
    }
}
