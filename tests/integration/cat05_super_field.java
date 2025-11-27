class Parent {
    int value = 10;
}

class Child extends Parent {
    int value = 20;

    void printValues() {
        System.out.println(value);
        System.out.println(super.value);
    }
}

public class TestSuperField {
    public static void main(String[] args) {
        Child c = new Child();
        c.printValues();
    }
}