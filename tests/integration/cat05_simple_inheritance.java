class Animal {
    String name;

    Animal(String name) {
        this.name = name;
    }

    String getName() {
        return name;
    }
}

class Dog extends Animal {
    Dog(String name) {
        super(name);
    }
}

public class TestInheritance {
    public static void main(String[] args) {
        Dog d = new Dog("Buddy");
        System.out.println(d.getName());
    }
}
