class A {
    int a = 1;
}

class B extends A {
    int b = 2;
}

class C extends B {
    int c = 3;
}

public class TestMultilevelInheritance {
    public static void main(String[] args) {
        C obj = new C();
        System.out.println(obj.a);
        System.out.println(obj.b);
        System.out.println(obj.c);
    }
}