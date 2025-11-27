class Point {
    int x;
    int y;

    Point(int x, int y) {
        this.x = x;
        this.y = y;
    }

    int getX() {
        return x;
    }
}

public class TestSimpleClass {
    public static void main(String[] args) {
        Point p = new Point(10, 20);
        System.out.println(p.getX());
        System.out.println(p.y);
    }
}
