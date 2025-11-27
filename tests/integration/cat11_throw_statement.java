public class TestThrow {
    static void checkAge(int age) {
        if (age < 18) {
            throw new RuntimeException("Too young");
        }
        System.out.println("Valid age");
    }

    public static void main(String[] args) {
        try {
            checkAge(20);
            checkAge(15);
        } catch (RuntimeException e) {
            System.out.println("Caught");
        }
    }
}