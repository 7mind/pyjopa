enum Size {
    SMALL(1),
    MEDIUM(2),
    LARGE(3);

    private int value;

    Size(int v) {
        value = v;
    }

    int getValue() {
        return value;
    }
}

public class TestEnumConstructor {
    public static void main(String[] args) {
        Size s = Size.MEDIUM;
        System.out.println(s.getValue());
    }
}
