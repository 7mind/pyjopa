class Person {
    String name;

    Person(String name) {
        this.name = name;
    }

    String getName() {
        return this.name;
    }
}

public class TestThis {
    public static void main(String[] args) {
        Person p = new Person("Alice");
        System.out.println(p.getName());
    }
}
