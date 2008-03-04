function export_BCD(ver,db,ma)
id = [num2str(ma) 'mA_' num2str(db) 'dB'];
infile = ['/home/diamond/common/matlab/middlelayer/' ver ...
    '/machine/diamondopsdata/SR/GoldenOrbit_' id '.mat'];
load(infile, 'golden')
x = zeros(168,1);
y = zeros(168,1);

x(golden.bpmlist) = 1e3*golden.x;
y(golden.bpmlist) = 1e3*golden.y;

outfile = ['/home/ops/diagnostics/bcd/BCD_' id '_'];
save([outfile 'X'], 'x', '-ascii')
save([outfile 'Y'], 'y', '-ascii')
