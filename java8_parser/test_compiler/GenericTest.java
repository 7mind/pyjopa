import java.util.ArrayList;
import java.util.List;

public class GenericTest<T> {
    private T value;

    public GenericTest(T value) {
        this.value = value;
    }

    public T getValue() {
        return value;
    }

    public <U> U transform(T input, U defaultValue) {
        return defaultValue;
    }

    public static void main(String[] args) {
        GenericTest<String> test = new GenericTest<String>("Hello");
        String v = test.getValue();
        System.out.println(v);

        List<Integer> list = new ArrayList<Integer>();
        list.add(42);
        System.out.println(list.get(0));
    }
}
