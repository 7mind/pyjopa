class Animal {
    String name;
    Animal(String n) {
        name = n;
    }
}

class Dog extends Animal {
    Dog(String n) {
        super(n);
    }
}

public class TestSuperConstructor {
    public static void main(String[] args) {
        Dog d = new Dog("Buddy");
        System.out.println(d.name);
    }
}