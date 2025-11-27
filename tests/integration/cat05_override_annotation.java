class Base {
    int getValue() {
        return 10;
    }
}

class Derived extends Base {
    @Override
    int getValue() {
        return 20;
    }
}

public class TestOverrideAnnotation {
    public static void main(String[] args) {
        Base b = new Derived();
        System.out.println(b.getValue());
    }
}