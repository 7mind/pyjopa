interface Drawable {
    void draw();
}

class Circle implements Drawable {
    public void draw() {
        System.out.println("drawing circle");
    }
}

public class TestInterface {
    public static void main(String[] args) {
        Circle c = new Circle();
        c.draw();
    }
}
