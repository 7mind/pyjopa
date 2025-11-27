public class TestIfElse {
    public static void main(String[] args) {
        int x = 10;
        if (x > 5) {
            System.out.println("greater");
        } else {
            System.out.println("smaller");
        }

        if (x == 5) {
            System.out.println("equal");
        } else if (x > 5) {
            System.out.println("greater");
        } else {
            System.out.println("smaller");
        }
    }
}
