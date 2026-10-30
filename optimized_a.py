import argparse
import os


def main(data_dir, out_dir):
    groups = {}
    input_path = os.path.join(data_dir, "requests.log")

    with open(input_path, "rb") as file:
        for line in file:
            ts, method, endpoint, status, latency = line.split(b" ")
            hour = ts[:13]
            key = (hour, endpoint)

            if key not in groups:
                groups[key] = [[], 0]

            group = groups[key]
            group[0].append(int(latency))

            if status[0] == ord("5"):
                group[1] += 1

    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "summary.txt")

    with open(output_path, "wb") as output:
        for (hour, endpoint), (latencies, errors) in sorted(groups.items()):
            latencies.sort()
            count = len(latencies)

            p50 = latencies[(50 * count + 99) // 100 - 1]
            p95 = latencies[(95 * count + 99) // 100 - 1]
            p99 = latencies[(99 * count + 99) // 100 - 1]
            error_ppm = errors * 1_000_000 // count

            result = (
                hour + b":00:00Z " + endpoint + b" "
                + str(count).encode() + b" "
                + str(p50).encode() + b" "
                + str(p95).encode() + b" "
                + str(p99).encode() + b" "
                + str(errors).encode() + b" "
                + str(error_ppm).encode() + b"\n"
            )
            output.write(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/data")
    parser.add_argument("--out", default="/out")
    args = parser.parse_args()
    main(args.data, args.out)
