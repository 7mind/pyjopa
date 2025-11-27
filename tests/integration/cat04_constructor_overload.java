class Box {
    int value;

    Box() {
        value = 0;
    }

    Box(int v) {
        value = v;
    }

    int getValue() {
        return value;
    }
}

public class TestConstructorOverload {
    public static void main(String[] args) {
        Box b1 = new Box();
        Box b2 = new Box(42);
        System.out.println(b1.getValue());
        System.out.println(b2.getValue());
    }
}
