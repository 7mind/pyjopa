class Base {
    String getMessage() {
        return "base";
    }
}

class Derived extends Base {
    String getMessage() {
        return super.getMessage() + "-derived";
    }
}

public class TestSuperMethod {
    public static void main(String[] args) {
        Derived d = new Derived();
        System.out.println(d.getMessage());
    }
}
