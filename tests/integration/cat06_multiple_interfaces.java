interface A {
    int getValue();
}

interface B {
    String getName();
}

class C implements A, B {
    public int getValue() {
        return 42;
    }

    public String getName() {
        return "test";
    }
}

public class TestMultipleInterfaces {
    public static void main(String[] args) {
        C c = new C();
        System.out.println(c.getValue());
        System.out.println(c.getName());
    }
}
