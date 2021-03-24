package aieng;

import java.io.IOException;
import java.util.StringTokenizer;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.io.VIntWritable;
import org.apache.hadoop.mapreduce.Mapper;

/**
 * Mapper Utility for word count.
 */
public class ratingMapper
        extends Mapper<Text, Text, Text, Text> {


    public void map(Text key, Text value, Context context
    ) throws IOException, InterruptedException {
        StringTokenizer itr = new StringTokenizer(value.toString());
        while (itr.hasMoreTokens()) {
            //let us process the logs here only for rating 
            //three types of logs
            String line = itr.nextToken();
            String userId = left.split(",")[0];
            String movieID= right.split(",")[1];
            String userID= right.split(",")[3];
            context.write(new Text(userId), new Text(movieID + "," + userID));
        }
    }
}