class Point {
    int x, y;

    Point() {
        this(0, 0);
    }

    Point(int x) {
        this(x, 0);
    }

    Point(int x, int y) {
        this.x = x;
        this.y = y;
    }
}

public class TestMultipleConstructors {
    public static void main(String[] args) {
        Point p1 = new Point();
        Point p2 = new Point(5);
        Point p3 = new Point(3, 4);
        System.out.println(p1.x + "," + p1.y);
        System.out.println(p2.x + "," + p2.y);
        System.out.println(p3.x + "," + p3.y);
    }
}