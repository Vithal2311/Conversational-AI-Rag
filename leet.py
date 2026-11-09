l1 = [2,3,7,4,3,9]
target = 9
s1 = []
for i  in l1:
    for j in l1:
        if i + j == target:
            s1.append(i)
print(s1)
