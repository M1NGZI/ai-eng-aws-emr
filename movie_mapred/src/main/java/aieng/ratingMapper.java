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
            // 1. <time>,<userid>,recommendation request <server>, status <200 for success>, result: <recommendations>, <responsetime>
            // 2. <time>,<userid>,GET /data/m/<movieid>/<minute>.mpg 
            // 3. rating <time>,<userid>,GET /rate/<movieid>=<rating>
            String line = itr.nextToken();
            String left = line.split(" ")[0];
            String right = line.split(" ")[1];
            String userId = left.split(",")[1];
            if(right.split("/")[1].equals("rate")){
                String movieID= right.split("/")[2].split("=")[0];
                String userID= right.split("/")[2].split("=")[1];
                context.write(new Text(userId), new Text(movieID + "," + userID));
            }
        }
    }
}