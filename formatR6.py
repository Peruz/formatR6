"""
rn are the row numbers in the input file, to check the correct merging and formatting (PGALA -> em).
Similarly, emtime, gpstime, and zdadate are all merged to check the possible time differences.
Each PGALA row (actual fdem data) is merged with:
1) the closest GNZDA row, earlier or successive (only date column).
2) the next GNGGA row is taken, i.e. closest but successive, as this often matches the PGALA time.
This should correctly handle the variability of the input file and possible format changes.
"""

import argparse
from pathlib import Path
import sys

try:
    import duckdb as db
except ImportError:
    raise ImportError('\nmissing duckdb module, install with: pip install duckdb')


parser = argparse.ArgumentParser()
parser.add_argument('datafile')
parser.add_argument('--height', help='height in m', default='0.1')
parser.add_argument('--freq', help='frequency in Hz', default='9000')
parser.add_argument('-d', '--database', default=None)
parser.add_argument('-t', '--table', default='data')

args = parser.parse_args()
datafile = args.datafile

datafile = Path(args.datafile)
outfile = datafile.with_name('out_' + datafile.name).with_suffix('.csv')
frequency = args.freq
height = args.height
database = args.database
table = args.table

if database is not None:
    conn = db.connect(database)
else:
    conn = db.connect()


cf1, cf2, cf3, cf4, cf5, cf6 = (225.1582, 114.8766, 69.4933, 46.5203, 25.0176, 14.8033)

format_data = f"""
create or replace table {table} as (

with raw_data as (
select * from read_csv('{datafile}', all_varchar=true, null_padding=true, sep=',', header=false)
),

numbered_data as (select row_number() over () as rn, * from raw_data order by rn),

pgala as (select rn,
column03 as emtime,
column04 as bvolt, column05 as bcur, column06 as tempc,
column07 as pitch, column08 as roll,
column09 as eca1, column10 as msa1,
column11 as eca2, column12 as msa2,
column13 as eca3, column14 as msa3,
column15 as eca4, column16 as msa4,
column17 as eca5, column18 as msa5,
column19 as eca6, column20[0:-4] as msa6
from numbered_data where column00 = '$PGALA'
order by rn
),

gngga as (select rn,
column01 as gpstime,
column02 as latitude, column04 as longitude, column09 as altitude,
column06 as quality, column07 as numsv, column08 as hdop
from numbered_data where column00 = '$GNGGA'
order by rn
),

gnzda as (select rn,
strptime(column04 || column03 || column02 || column01, '%Y%m%d%H%M%S.%f') as date
from numbered_data where column00 = '$GNZDA'
order by rn
),

joined_data as (select
pgala.rn as emrn,
gngga.rn as ggarn,
case when (gnzdafwd.rn - emrn) > (emrn - gnzdabwd.rn)
then gnzdabwd.rn
else ifnull(gnzdafwd.rn, gnzdabwd.rn)
end as zdarn,
case when (gnzdafwd.rn - emrn) > (emrn - gnzdabwd.rn)
then gnzdabwd.date
else ifnull(gnzdafwd.date, gnzdabwd.date)
end as zdadate,
cast(strptime(emtime, '%H%M%S.%f') as time) as emtime,
cast(strptime(gpstime, '%H%M%S.%f') as time) as gpstime,
cast(latitude[:2] as double) + (cast(latitude[3:] as double) / 60) as latitude,
cast(longitude[:3] as double) + (cast(longitude[4:] as double) / 60) as longitude,
cast(numsv as integer) as numsv,
cast(hdop as double) as hdop,
cast(bvolt as double) as bvolt, cast(bcur as double) as bcur, cast(tempc as double) as tempc,
cast(pitch as double) as pitch, cast(roll as double) as roll,
cast(eca1 as double) as eca1, cast(msa1 as double) as msa1,
cast(eca2 as double) as eca2, cast(msa2 as double) as msa2,
cast(eca3 as double) as eca3, cast(msa3 as double) as msa3,
cast(eca4 as double) as eca4, cast(msa4 as double) as msa4,
cast(eca5 as double) as eca5, cast(msa5 as double) as msa5,
cast(eca6 as double) as eca6, cast(msa6 as double) as msa6
from pgala
asof left join gngga on pgala.rn <= gngga.rn
asof left join gnzda as gnzdafwd on pgala.rn <= gnzdafwd.rn
asof left join gnzda as gnzdabwd on pgala.rn >= gnzdabwd.rn
order by pgala.rn
)

select *,
round(eca1 / {cf1}, 6) as "HCP0.5f{frequency}h{height}_quad",
round(eca2 / {cf2}, 6) as "HCP0.7f{frequency}h{height}_quad",
round(eca3 / {cf3}, 6) as "HCP0.9f{frequency}h{height}_quad",
round(eca4 / {cf4}, 6) as "HCP1.1f{frequency}h{height}_quad",
round(eca5 / {cf5}, 6) as "HCP1.5f{frequency}h{height}_quad",
round(eca6 / {cf6}, 6) as "HCP1.9f{frequency}h{height}_quad",
from joined_data order by emrn
);
copy data to '{outfile}' (header, delimiter ',');
"""
conn.sql(format_data)
print('formatted file: ', outfile)
