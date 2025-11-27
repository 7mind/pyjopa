import java.util.ArrayList;
import java.util.List;

public class TestWildcards {
    // Upper bounded wildcard
    public static Number getFirst(List<? extends Number> list) {
        if (list.size() > 0) {
            return list.get(0);
        }
        return null;
    }

    // Lower bounded wildcard
    public static void addInteger(List<? super Integer> list) {
        list.add(42);
    }

    // Unbounded wildcard
    public static int getSize(List<?> list) {
        return list.size();
    }

    public static void main(String[] args) {
        // Test upper bounded wildcard with Integer list
        List<Integer> integers = new ArrayList<Integer>();
        integers.add(1);
        integers.add(2);
        Number first = getFirst(integers);
        System.out.println(first);

        // Test lower bounded wildcard
        List<Number> numbers = new ArrayList<Number>();
        addInteger(numbers);
        System.out.println(numbers.size());

        // Test unbounded wildcard
        int size = getSize(integers);
        System.out.println(size);
    }
}
