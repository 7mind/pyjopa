class Base {
    public final int getValue() {
        return 42;
    }
}

public class TestFinalMethod extends Base {
    public static void main(String[] args) {
        TestFinalMethod obj = new TestFinalMethod();
        System.out.println(obj.getValue());
    }
}