pragma circom 2.0.0;

template IsEqual() {
    signal input a;
    signal input b;
    signal output out;

    out <== 1 - (a - b) * (a - b);
}

template AccessControl() {
    signal input role;
    signal input department;
    signal input authorized;
    signal output isAccessGranted;

    component roleCheck = IsEqual();
    component deptCheck = IsEqual();
    component authCheck = IsEqual();

    roleCheck.a     <== role;
    roleCheck.b     <== 1;

    deptCheck.a     <== department;
    deptCheck.b     <== 2;

    authCheck.a     <== authorized;
    authCheck.b     <== 1;

    signal intermediate;

    intermediate <== roleCheck.out * deptCheck.out;
    isAccessGranted <== intermediate * authCheck.out;

}

component main = AccessControl();
