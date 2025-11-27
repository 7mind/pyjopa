class Shape {
    String getType() {
        return "shape";
    }
}

class Circle extends Shape {
    String getType() {
        return "circle";
    }
}

public class TestOverride {
    public static void main(String[] args) {
        Shape s = new Shape();
        Circle c = new Circle();
        System.out.println(s.getType());
        System.out.println(c.getType());
    }
}
