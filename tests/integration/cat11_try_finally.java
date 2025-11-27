public class TestFinally {
    public static void main(String[] args) {
        try {
            System.out.println("try");
        } finally {
            System.out.println("finally");
        }
        System.out.println("end");
    }
}
