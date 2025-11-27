public class TestFinalField {
    private final int value = 100;

    public static void main(String[] args) {
        TestFinalField obj = new TestFinalField();
        System.out.println(obj.value);
    }
}