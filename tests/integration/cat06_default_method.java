interface Greet {
    default String greet() {
        return "Hello";
    }
}

class Person implements Greet {
}

public class TestDefaultMethod {
    public static void main(String[] args) {
        Person p = new Person();
        System.out.println(p.greet());
    }
}