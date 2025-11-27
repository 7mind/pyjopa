public class TestConstructorChaining {
    private int value;

    public TestConstructorChaining() {
        this(42);
    }

    public TestConstructorChaining(int v) {
        value = v;
    }

    public static void main(String[] args) {
        TestConstructorChaining obj = new TestConstructorChaining();
        System.out.println(obj.value);
    }
}