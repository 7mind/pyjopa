abstract class Shape {
    abstract int getArea();
}

class Rectangle extends Shape {
    int width = 4;
    int height = 5;

    int getArea() {
        return width * height;
    }
}

public class TestAbstractClass {
    public static void main(String[] args) {
        Shape s = new Rectangle();
        System.out.println(s.getArea());
    }
}