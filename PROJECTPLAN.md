# Project: redot2koinly

Convert screenshots of Redotpay's transaction history to Koinly's simple transaction template csv file.

# Inputs

- Optional: A screenshots directory or file name. The file name must be of type jpeg/jpg/png. The directory is searched for screenshot files (sub-directories are not searched). Default is the project's data sub-directory
- Optional: The output file name. Default is redotpay.csv
- Optional: Timezone of the dates in the redotpay history log. Default is the local (computer) timezone.
- Optional: Year. The history log dates do not include the year. Default is the previous year, as the assumption is that the processing is done for tax purposes. No support for transactions from multiple years (add to limitations).   

# Outputs
 - Transaction csv log file in Koinly's [simple template](https://support.koinly.io/en/articles/9489976-how-to-create-a-custom-csv-file-with-your-data) format.
 - Duplicate transactions are removed. Duplicate transaction have the same Koinly date and label.
 - Transactions are ordered by Koinly date in ascending order
 - Processing statistics including the number of input files processed, the number of files that  hence ignored, the time it took to run the program, the number of transactions read, the number of transactions dropped when eliminating duplication and the number of record reading errors.
 
# Redotpay screenshot format

- A sample screenshot eth.jpg is available under the tests subdirectory.
- The screenshot includes a header with some icons and a line that include the word 'History' in the middle. If a screenshot fails to include the header it should be counted in the number of ignored input files. Otherwise this information should be ignored.
- The end of the history log is marked in the application with a 'No more records' line. If non of the screenshots includes this line, a warning should be printed to the log. Otherwise this line is ingored.
- The transaction entries are grouped into one or more transaction records by date. The date appears first before the transaction records with the 'Day, Mon DD' format, e.g. 'Wed, Sep 3'. The screenshot is scanned until the first line with such date is found. Previous entries are ignored. If no such line is found, the number of ingored input files is increased. A screenshot may not have the transactions date as first item after the header. The project assumes that the number of transactions done daily is small enough to fit into a single screenshot (add to limitations).
- Each transaction record is composed of the following fields organized in the screenshot as specified in the ascii drawing below:

```
+------+---------------+----------+----------+
|      | merchant      |          |          |
| icon +--------+------+   amount | currency |
|      | prefix | time |          |          |
+------+--------+------+----------+----------+
```

- The transaction record fields screenshot read processing is defined in the table below:

| Field    | Format                                                                                  | Example     | Processing |
| -------- | --------------------------------------------------------------------------------------- | ----------- | ---------- |
| icon     | icon                                                                                    |             | ignored    |
| merchant | text                                                                                    | Lush GmbH   | saved      |
| amount   | signed decimal                                                                          | -0.06053524 | saved      |
| currency | 3 uppercase chars                                                                       | ETH         | saved      |
| prefix   | Either text if amount is positive, or 4 dots followed by 4 digits if amount is negative | Wallet      | ignored    |
| time     | HH:MM:SS                                                                                | 14:30:03    | saved      |

# Koinly file csv format

- The following are the columns in the output file:

| Column | Title       | Processing                                                         |
| ------ | ----------- | ------------------------------------------------------------------ |
| A      | Koinly Date | transaction date + time converted to UTC e.g. 2018-01-01 14:25 UTC | \ |
| B      | Amount      | transaction amount                                                 |
| C      | Currency    | transaction currency                                               |
| D      | Lable       | transaction merchant                                               |
| E      | TxHash      | leave blank                                                        |

# Additional error detection
- A screenshot file error1.jpeg is available under the tests sub-directory. Processing of this file should detect record processing error. 
