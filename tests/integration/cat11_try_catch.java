public class TestTryCatch {
    public static void main(String[] args) {
        try {
            int x = 10 / 2;
            System.out.println(x);
        } catch (Exception e) {
            System.out.println("error");
        }
        System.out.println("done");
    }
}
