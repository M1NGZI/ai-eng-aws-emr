package aieng;

import java.io.IOException;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.io.VIntWritable;
import org.apache.hadoop.mapreduce.Reducer;

public class ratingReducer
        extends Reducer<Text, Text, Text, Text> {
    public void reduce(Text key, Iterable<Text> values, Context context)
            throws IOException, InterruptedException {
        String res = "";
        for (Text movieidRatingPairs: values) {
            res += movieidRatingPairs.toString() + "\t";
        }
        context.write(key, new Text(res));
    }
}