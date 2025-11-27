interface A {
    int getA();
}

interface B extends A {
    int getB();
}

class Impl implements B {
    public int getA() { return 1; }
    public int getB() { return 2; }
}

public class TestInterfaceExtends {
    public static void main(String[] args) {
        Impl obj = new Impl();
        System.out.println(obj.getA());
        System.out.println(obj.getB());
    }
}